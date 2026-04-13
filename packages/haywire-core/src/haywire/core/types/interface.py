from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from haywire.core.types.enums import PortType, StoreStrategy

if TYPE_CHECKING:
    from ..library.identity import LibraryIdentity
    from . import DataPort, DataField, PortSpec, DataTypeIdentity

# ============================================================================
# ROOT INTERFACE WITH SHARED IMPLEMENTATIONS
# ============================================================================


class IType(ABC):
    """
    Abstract base for Haywire type system.

    ARCHITECTURE:

    Type System (IType):
        - Describes data types (metadata, ports, adapters)
        - Can be instantiated for adapters and defaults
        - Instances are TEMPLATES, not runtime storage

    Storage System (DataField):
        - Stores actual runtime data efficiently
        - Uses unwrapped values for primitives
        - Uses instances for complex types

    TWO PATTERNS:

    1. PRIMITIVES (FLOAT, INT, STRING)
       - Type: FLOAT class (descriptor)
       - Instance: FLOAT(value=42.0) (template for adapters/defaults)
       - Storage: 42.0 (unwrapped in PrimitiveField)

    2. BASE (MeshData, Vector3)
       - Type: MeshData class (descriptor AND data container)
       - Instance: MeshData(...) (descriptor instance IS the data)
       - Storage: MeshData(...) instance (in BaseField)

    The .value property provides uniform interface:
    - PrimitiveType.value → unwrapped primitive
    - BaseType.value → self (instance is the value)

    HIERARCHICAL TYPE SYSTEM:

    element_type_cls creates a hierarchical structure:
    - PrimitiveType: Points to Python primitive (float, str, int, bool)
    - BaseType: Points to itself (the class IS the element type)
    - CompoundType: Points to IType of elements (FLOAT, MeshData)

    This enables drilling down through type layers:
        ArrayType[FLOAT].element_type_cls → FLOAT
        FLOAT.element_type_cls → float

    **Abstract Requirements** (subclasses must implement):
    - value property: Returns the type's data in natural form

    **Concrete Defaults** (subclasses inherit, can override):
    - as_inlet/as_outlet/as_config: Port creation methods
    - create_field: DataField creation
    - _validate_port_type: Port type validation hook (default: allow all)
    - _configure_port: Port configuration hook (default: no config)

    **Class Attributes** (subclasses must set):
    - field_class: DataField class that handles storage
    - element_type_cls: What this type wraps/contains (set automatically)

    This follows Python's ABC pattern where base classes provide both
    abstract requirements and concrete default implementations.

    Attributes (set by @type decorator):
        class_identity: DataTypeIdentity with all type metadata
        class_library: LibraryIdentity of the library this type belongs to
    """

    # STRUCTURAL ATTRIBUTES (type system mechanics)
    field_class: type["DataField"] = None
    # DataField class responsible for storing this type's data.
    # Subclasses MUST set this to their corresponding DataField subclass.
    # This allows the type to create its own field instances with the correct configuration.

    element_type_cls: type = None
    # What this type wraps/contains

    # IDENTITY ATTRIBUTES (set by @type decorator)
    class_identity: "DataTypeIdentity"
    class_library: "LibraryIdentity"

    @property
    @abstractmethod
    def value(self):
        """
        Returns the value of this type in its natural form.

        For PrimitiveType: returns the unwrapped primitive (42.0, "hello")
        For BaseType: returns self (the instance IS the value)
        For CompoundType: returns the container (list, dict, etc.)
        """
        pass

    # ========================================================================
    # FIELD CREATION - Type creates its own field
    # ========================================================================

    @classmethod
    def create_field(cls, default_override: Optional[Dict[str, Any]] = None) -> "DataField":
        """
        Create the DataField for this type.

        Each type is responsible for creating its own field instance.
        This replaces the DataFieldFactory pattern - types know what they need!

        Args:
            default_override: Override default kwargs from @type decorator

        Returns:
            Configured DataField instance

        Raises:
            ValueError: If field_class not declared

        Examples:
            # Simple type
            field = FLOAT.create_field()

            # Compound type
            field = ArrayType.create_field()
        """
        if not cls.field_class:
            raise ValueError(
                f"{cls.__name__} doesn't declare field_class. "
                f"Add 'field_class = SomeField' to the type definition."
            )

        # Get default kwargs
        default_kwargs = default_override or {}
        if not default_kwargs and hasattr(cls, "class_identity"):
            default_kwargs = getattr(cls.class_identity, "default", {})

        return cls.field_class(type_cls=cls, default_kwargs=default_kwargs)

    # ========================================================================
    # HOOKS - Subclasses override to customize behavior
    # ========================================================================

    @classmethod
    def _validate_port_type(cls, port_type: PortType) -> None:
        """
        Validate if this type supports the given port type.

        Hook for subclasses to restrict which port types they support.
        Default implementation allows all port types.

        Args:
            port_type: PortType

        Raises:
            ValueError: If this type doesn't support the port type

        Examples:
            # Override to restrict
            class PooledType(CompoundType):
                @classmethod
                def _validate_port_type(cls, port_type: PortType):
                    if port_type != PortType.INLET:
                        raise ValueError("PooledType only supports inlets")
        """
        pass  # Default: all port types allowed

    @classmethod
    def _configure_port(cls, port: "DataPort", **context) -> None:
        """
        Configure port-specific attributes after creation.

        Hook for subclasses to add custom port configuration.
        Default implementation does nothing.

        Args:
            port: Port to configure
            **context: Additional context (element_type_cls, etc.)

        Examples:
            # Override to configure
            class PooledType(CompoundType):
                @classmethod
                def _configure_port(cls, port, **context):
                    port.allow_multiple_links = True
        """
        pass  # Default: no extra configuration

    # ========================================================================
    # PORT CREATION - Returns PortSpec for node.add() to instantiate
    # ========================================================================

    @classmethod
    def as_inlet(cls, id: str, **kwargs) -> "PortSpec":
        """
        Create an inlet specification from this type.

        Returns a PortSpec dict, not a port instance. The node's add()
        method uses this spec to instantiate the actual DataPort.

        Sets the store_strategy to WIDGET
        (only stores widget data when saving the graph)

        Universal implementation that works for all type categories:
        - PrimitiveType: FLOAT.as_inlet('value', default=0.0)
        - BaseType: MeshData.as_inlet('mesh', default={...})
        - CompoundType: Uses parameterized syntax (see below)

        For CompoundType, use parameterized syntax:
            ArrayType[FLOAT].as_inlet('numbers')
            PooledType[MeshData].as_inlet('meshes')

        Args:
            id: Port identifier
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
                    (default: WIDGET if not set on type identity)
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
                use_mode (str): 'optional' or 'required' (default: 'optional')

            Callbacks:
                on_change (str): Node method name to call when value changes
                on_connect (str): Node method name to call when connected
                on_disconnect (str): Node method name to call when disconnected

        Returns:
            PortSpec dict for node.add()

        Examples:
        .. code-block:: python
            self.add(FLOAT.as_inlet('value', default=1.0))
            self.add(FLOAT.as_inlet('threshold', default=0.5,
                     widget=SliderWidget.config(min=0.0, max=1.0)))
            self.add(ArrayType[FLOAT].as_inlet('numbers', default=[1.0, 2.0]))
            self.add(PooledType[FLOAT].as_inlet('values'))
            self.add(FLOAT.as_inlet('param', on_change='on_param_changed'))
        """
        from haywire.core.types.utils import create_port_spec

        # Validate port type
        cls._validate_port_type(PortType.INLET)

        kwargs.setdefault("store_strategy", cls._resolve_store_strategy(StoreStrategy.HAS_WIDGET))
        return create_port_spec(cls, id=id, port_type=PortType.INLET, **kwargs)

    @classmethod
    def as_outlet(cls, id: str, **kwargs) -> "PortSpec":
        """
        Create an outlet specification from this type.

        Returns a PortSpec dict, not a port instance. The node's add()
        method uses this spec to instantiate the actual DataPort.

        Sets the store_strategy to STORE
        (stores when saving the graph)

        Note: Data-flow outlets automatically get allow_multiple_links=True.

        Args:
            id: Port identifier

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
                needs_loopback (bool): Set to True if the control flow from
                    this outlet needs to loop back to the node (default: False)

            Callbacks:
                on_change (str): Node method name to call when value changes
                on_connect (str): Node method name to call when connected
                on_disconnect (str): Node method name to call when disconnected

        Returns:
            PortSpec dict for node.add()

        Examples:
        .. code-block:: python
            self.add(FLOAT.as_outlet('result'))
            self.add(ArrayType[FLOAT].as_outlet('sorted'))
            self.add(CTRL.as_outlet('loop_body', needs_loopback=True))
        """
        from haywire.core.types.utils import create_port_spec

        # Validate port type
        cls._validate_port_type(PortType.OUTLET)

        kwargs.setdefault("store_strategy", cls._resolve_store_strategy(StoreStrategy.ALWAYS))
        return create_port_spec(cls, id=id, port_type=PortType.OUTLET, **kwargs)

    @classmethod
    def as_config(cls, id: str, **kwargs) -> "PortSpec":
        """
        Create a config inlet specification (no visible pin) from this type.

        Config inlets are internal parameters that don't show as connection pins.
        Returns a PortSpec dict, not a port instance.

        Sets flow_type to NONE and store_strategy to STORE
        (always stores when saving the graph)

        Args:
            id: Config identifier

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
                use_mode (str): 'optional' or 'required' (default: 'optional')

            Callbacks:
                on_change (str): Node method name to call when value changes

        Returns:
            PortSpec dict for node.add() with flow_type=NONE

        Examples:
        .. code-block:: python
            self.add(FLOAT.as_config('threshold', default=0.5))
            self.add(FLOAT.as_config('speed', default=1.0,
                     widget=SliderWidget.config(min=0.0, max=10.0)))
            self.add(ArrayType[STRING].as_config('tags', default=['a', 'b']))
        """
        from haywire.core.types.enums import FlowType
        from haywire.core.types.utils import create_port_spec

        # Validate port type
        cls._validate_port_type(PortType.CONFIG)

        kwargs["flow_type"] = FlowType.NONE
        kwargs.setdefault("store_strategy", cls._resolve_store_strategy(StoreStrategy.ALWAYS))

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
