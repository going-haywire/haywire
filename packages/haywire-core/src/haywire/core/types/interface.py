from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional

from haywire.core.types.enums import PortType, StoreStrategy, default_show_widget

if TYPE_CHECKING:
    from ..library.identity import LibraryIdentity
    from . import DataPort, DataField, PortSpec, DataTypeIdentity

# ============================================================================
# ROOT INTERFACE WITH SHARED IMPLEMENTATIONS
# ============================================================================


class IType(ABC):
    """Root of the type system: what a value is, apart from where it is stored.

    A type describes data — its metadata, the ports it can build, the adapters
    it takes part in. An instance is a template used for defaults and adapters;
    runtime values live in the ``DataField`` the type builds through
    :meth:`create_field`.

    Four families derive from this base, each answering ``element_type_cls``
    differently:

    - ``PrimitiveType`` (``FLOAT``, ``INT``, ``STRING``) — one primitive,
      stored unwrapped. ``element_type_cls`` is the Python type. Cannot hold
      ``None``: ``PrimitiveType.__init__`` raises on one.
    - ``BaseType`` (``MeshData``, ``Vector3``) — one structured instance, which
      is both descriptor and data. ``element_type_cls`` is the class itself.
    - ``CompoundType`` (``ArrayType[FLOAT]``) — N elements of one type, from
      ``__class_getitem__``. ``element_type_cls`` is the element type. Other
      subsystems dispatch on this family to mean "container": ``AdapterFactory``
      builds element-wise chains for it and ``pin_render`` gives it collection
      iconography, so a type that holds one value must not subclass it.
    - ``WrapperType`` (``OPTIONAL[INT]``) — one value of another type, or
      absence, parameterized the same way. ``element_type_cls`` is the wrapped
      type. See ADR 0033.

    Nesting reads back through ``element_type_cls``, so
    ``ArrayType[FLOAT].element_type_cls`` is ``FLOAT`` and
    ``FLOAT.element_type_cls`` is ``float``.

    Subclasses must implement :attr:`value`, :meth:`to_dict` and
    :meth:`from_dict`, and set ``field_class``. Port creation and
    :meth:`create_field` are inherited; :meth:`_validate_port_type` and
    :meth:`_configure_port` are hooks that do nothing by default.
    """

    field_class: type["DataField"] | None = None

    element_type_cls: type | None = None

    _is_any: bool = False
    """Whether this type is the undecided placeholder (``ANY``).

    ``AdapterFactory.create_chain`` returns a pass-through for any pair with one
    end flagged, so an edge involving ``ANY`` is always valid and no adapter is
    ever looked up. See :class:`~haywire.barn.builtin.types.any.ANY`.
    """

    # Stamped by the @type decorator; absent on an undecorated subclass.
    class_identity: ClassVar["DataTypeIdentity"]
    class_library: ClassVar["LibraryIdentity"]

    @property
    @abstractmethod
    def value(self):
        """This instance's data in its natural form.

        A primitive returns the unwrapped value, a ``BaseType`` returns
        ``self``, a ``CompoundType`` its container, a ``WrapperType`` the
        wrapped value or ``None``.
        """
        pass

    # ========================================================================
    # SERIALIZATION - Subclasses implement
    # ========================================================================

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize this instance to a dict :meth:`from_dict` can read back.

        A primitive writes ``{'value': self.value}``; a ``BaseType`` defines
        its own structure.
        """
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> Any:
        """Read back what :meth:`to_dict` wrote, as this type's natural value.

        A primitive returns the unwrapped value, a ``BaseType`` an instance.
        """
        ...

    # ========================================================================
    # FIELD CREATION - Type creates its own field
    # ========================================================================

    @classmethod
    def create_field(cls, default_override: Optional[Dict[str, Any]] = None) -> "DataField":
        """Build the ``DataField`` that stores values of this type.

        Args:
            default_override: Constructor kwargs for the field's initial value,
                replacing the ``default`` the ``@type`` decorator declared. An
                empty dict counts as absent and the declared default is used.

        Raises:
            ValueError: If the type declares no ``field_class``.

        Example::

            field = FLOAT.create_field()
            field = FLOAT.create_field({"value": 1.5})
        """
        if not cls.field_class:
            raise ValueError(
                f"{cls.__name__} doesn't declare field_class. "
                f"Add 'field_class = SomeField' to the type definition."
            )

        default_kwargs = default_override or {}
        if not default_kwargs and hasattr(cls, "class_identity"):
            default_kwargs = getattr(cls.class_identity, "default", {})

        return cls.field_class(type_cls=cls, default_kwargs=default_kwargs)

    # ========================================================================
    # HOOKS - Subclasses override to customize behavior
    # ========================================================================

    @classmethod
    def _validate_port_type(cls, port_type: PortType) -> None:
        """Reject a port type this type cannot be used as. Accepts all by default.

        Override to restrict, raising ``ValueError`` for a port type the type
        does not support::

            class PooledType(CompoundType):
                @classmethod
                def _validate_port_type(cls, port_type: PortType):
                    if port_type != PortType.INLET:
                        raise ValueError("PooledType only supports inlets")
        """
        pass

    @classmethod
    def _configure_port(cls, port: "DataPort", **context) -> None:
        """Adjust a freshly created port. Does nothing by default.

        Called from ``DataPort.from_spec`` with no context, so an override
        must read what it needs off ``port`` and ``cls``.

        Override to set attributes the type always wants::

            class PooledType(CompoundType):
                @classmethod
                def _configure_port(cls, port, **context):
                    port.allow_multiple_links = True
        """
        pass

    # ========================================================================
    # PORT CREATION - Returns PortSpec for node.add() to instantiate
    # ========================================================================

    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> "PortSpec":
        """Build an inlet spec for ``node.add()``, which instantiates the ``DataPort``.

        ``store_strategy`` defaults to ``HAS_WIDGET``, so the value is saved
        with the graph only when the port has a widget. Compound and wrapper
        types are subscripted first (``ArrayType[FLOAT].as_inlet('numbers')``).

        Args:
            id: Port identifier, unique within the node.
            **kwargs: Override identity or port attributes. All values below
                are inherited from the type's class_identity and can be
                overridden per-port.

            Identity:
                label (str): Display name (auto-generated from id if omitted)
                description (str): Human-readable description

            Type configuration:
                default (dict | primitive): Default value. Primitives auto-wrap
                    to {'value': ...} for PrimitiveType subclasses
                flow_type (FlowType): DATA, CONTROL, CALLBACK, or NONE
                    (default: DATA)
                store_strategy (StoreStrategy): NEVER, HAS_WIDGET, WHEN_LINKED, NODE_SET or ALWAYS
                    (default: HAS_WIDGET if not set on type identity)
                color (str): Pin color as hex string (e.g. '#FF0000')
                icon (str): Pin icon (sets all icon variants)
                icon_in (str): Icon for inlet pin
                icon_in_multi (str): Icon for multi-link inlet pin
                icon_out (str): Icon for outlet pin
                icon_out_multi (str): Icon for multi-link outlet pin
                widget_key (str): Widget key for value editing (preferably use widget instead)
                widget_config (dict): Widget configuration parameters (preferably use widget instead)
                help_url (str): Documentation link

            Port behavior:
                widget (dict): Transient widget config dict with 'key' and
                    optional 'config' fields. Decomposed into widget_key and
                    widget_config during port creation. Use
                    WidgetClass.config(**kwargs) to generate correct format
                allow_multiple_links (bool): Allow multiple incoming
                    connections (default: False)
                show_widget (ShowWidgetStrategy): When the inline widget is
                    rendered relative to link state — NEVER, NOT_LINKED,
                    WHEN_LINKED, ALWAYS (default: NOT_LINKED for inlets)
                use_mode (str): 'optional' or 'required' (default: 'optional')

            Callbacks:
                on_change (str): Node method name to call when value changes
                on_connect (str): Node method name to call when connected
                on_disconnect (str): Node method name to call when disconnected

        Example::

            self.add(FLOAT.as_inlet('value', default=1.0))
            self.add(FLOAT.as_inlet('threshold', default=0.5,
                     widget=SliderWidget.config(min=0.0, max=1.0)))
            self.add(ArrayType[FLOAT].as_inlet('numbers', default=[1.0, 2.0]))
            self.add(PooledType[FLOAT].as_inlet('values'))
            self.add(FLOAT.as_inlet('param', on_change='on_param_changed'))
        """
        from haywire.core.types.utils import create_port_spec

        cls._validate_port_type(PortType.INLET)

        kwargs.setdefault("store_strategy", cls._resolve_store_strategy(StoreStrategy.HAS_WIDGET))
        kwargs.setdefault("show_widget", default_show_widget(PortType.INLET))
        return create_port_spec(cls, id=id, port_type=PortType.INLET, **kwargs)

    @classmethod
    def as_outlet(cls, id: str, **kwargs) -> "PortSpec":
        """Build an outlet spec for ``node.add()``, which instantiates the ``DataPort``.

        The value is saved with the graph, and compound and wrapper types are
        subscripted first (``ArrayType[FLOAT].as_outlet('sorted')``).

        Args:
            id: Port identifier, unique within the node.

            **kwargs: Override identity or port attributes. All values below
                are inherited from the type's class_identity and can be
                overridden per-port.

            Identity:
                label (str): Display name (auto-generated from id if omitted)
                description (str): Human-readable description
                deprecation_warning (str): Deprecation warning message

            Type configuration:
                default (dict | primitive): Default value. Primitives auto-wrap
                    to {'value': ...} for PrimitiveType subclasses
                flow_type (FlowType): DATA, CONTROL, CALLBACK, or NONE
                    (default: DATA)
                store_strategy (StoreStrategy): NEVER, HAS_WIDGET, WHEN_LINKED, NODE_SET or ALWAYS
                    (default: ALWAYS if not set on type identity)
                color (str): Pin color as hex string (e.g. '#FF0000')
                icon (str): Pin icon (sets all icon variants)
                icon_in (str): Icon for inlet pin
                icon_in_multi (str): Icon for multi-link inlet pin
                icon_out (str): Icon for outlet pin
                icon_out_multi (str): Icon for multi-link outlet pin
                widget_key (str): Widget key for value editing (preferably use widget instead)
                widget_config (dict): Widget configuration parameters (preferably use widget instead)
                help_url (str): Documentation link

            Port behavior:
                widget (dict): Transient widget config dict with 'key' and
                    optional 'config' fields. Decomposed into widget_key and
                    widget_config during port creation. Use
                    WidgetClass.config(**kwargs) to generate correct format
                allow_multiple_links (bool): Allow multiple outgoing
                    connections (default: True for DATA flow)
                show_widget (ShowWidgetStrategy): When the inline widget is
                    rendered relative to link state — NEVER, NOT_LINKED,
                    WHEN_LINKED, ALWAYS (default: NEVER for outlets)
                needs_loopback (bool): Set to True if the control flow from
                    this outlet needs to loop back to the node (default: False)

            Callbacks:
                on_change (str): Node method name to call when value changes
                on_connect (str): Node method name to call when connected
                on_disconnect (str): Node method name to call when disconnected

        Example::

            self.add(FLOAT.as_outlet('result'))
            self.add(ArrayType[FLOAT].as_outlet('sorted'))
            self.add(CTRL.as_outlet('loop_body', needs_loopback=True))
        """
        from haywire.core.types.utils import create_port_spec

        cls._validate_port_type(PortType.OUTLET)

        kwargs.setdefault("store_strategy", cls._resolve_store_strategy(StoreStrategy.ALWAYS))
        kwargs.setdefault("show_widget", default_show_widget(PortType.OUTLET))
        return create_port_spec(cls, id=id, port_type=PortType.OUTLET, **kwargs)

    @classmethod
    def as_config(cls, id: str, **kwargs) -> "PortSpec":
        """Build a config spec for ``node.add()``: a parameter with a widget but no pin.

        ``flow_type`` is forced to ``NONE``, so a config can never be linked,
        and its value is saved with the graph.

        Args:
            id: Config identifier, unique among the node's ports.

            **kwargs: Override identity or port attributes. All values below
                are inherited from the type's class_identity and can be
                overridden per-port.

            Identity:
                label (str): Display name (auto-generated from id if omitted)
                description (str): Human-readable description
                deprecation_warning (str) : Deprecation warning message

            Type configuration:
                default (dict | primitive): Default value. Primitives auto-wrap
                    to {'value': ...} for PrimitiveType subclasses
                store_strategy (StoreStrategy): NEVER, HAS_WIDGET, WHEN_LINKED, NODE_SET or ALWAYS
                    (default: ALWAYS if not set on type identity)
                color (str): Pin color as hex string (e.g. '#FF0000')
                widget_key (str): Widget key for value editing (preferably use widget instead)
                widget_config (dict): Widget configuration parameters (preferably use widget instead)
                help_url (str): Documentation link

            Port behavior:
                widget (dict): Transient widget config dict with 'key' and
                    optional 'config' fields. Decomposed into widget_key and
                    widget_config during port creation. Use
                    WidgetClass.config(**kwargs) to generate correct format
                show_widget (ShowWidgetStrategy): When the inline widget is
                    rendered. Config ports are never linked, so NOT_LINKED/ALWAYS
                    both show and WHEN_LINKED hides (default: ALWAYS for config)
                use_mode (str): 'optional' or 'required' (default: 'optional')

            Callbacks:
                on_change (str): Node method name to call when value changes

        Example::

            self.add(FLOAT.as_config('threshold', default=0.5))
            self.add(FLOAT.as_config('speed', default=1.0,
                     widget=SliderWidget.config(min=0.0, max=10.0)))
            self.add(ArrayType[STRING].as_config('tags', default=['a', 'b']))
        """
        from haywire.core.types.enums import FlowType
        from haywire.core.types.utils import create_port_spec

        cls._validate_port_type(PortType.CONFIG)

        kwargs["flow_type"] = FlowType.NONE
        kwargs.setdefault("store_strategy", cls._resolve_store_strategy(StoreStrategy.ALWAYS))
        kwargs.setdefault("show_widget", default_show_widget(PortType.CONFIG))

        return create_port_spec(cls, id=id, port_type=PortType.CONFIG, **kwargs)

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    @classmethod
    def _resolve_store_strategy(cls, method_default: StoreStrategy) -> StoreStrategy:
        """Return the type identity's store_strategy if set, otherwise the method default."""
        if hasattr(cls, "class_identity"):
            identity_ss = cls.class_identity.store_strategy
            if identity_ss != StoreStrategy.NONE:
                return identity_ss
        return method_default

    def is_value_type(self, compare: type) -> bool:
        """Check if the value is of a specific type"""
        return isinstance(self.value, compare)

    @classmethod
    def create_default(cls):
        """
        Create a default instance.

        Default implementation uses the 'default' dict from @type decorator
        as constructor kwargs. Override this method for complex default logic.

        Returns:
            New instance with default values
        """
        default_kwargs = (
            getattr(cls.class_identity, "default", None) if hasattr(cls, "class_identity") else None
        )
        if default_kwargs is None:
            default_kwargs = {}

        try:
            return cls(**default_kwargs)
        except Exception as e:
            raise TypeError(
                f"Cannot create default instance of {cls.__name__} using default={default_kwargs}. "
                f"Consider overriding create_default() classmethod. "
                f"Original error: {e}"
            ) from e
