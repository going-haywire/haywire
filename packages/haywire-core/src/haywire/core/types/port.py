"""
DataPort Class - Unified port for inlets and outlets.

This module provides the DataPort class that integrates with the DataField hierarchy.
Direction is determined by the is_inlet field (True for inlet, False for outlet).
"""

from __future__ import annotations
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Dict, Optional, TYPE_CHECKING

from haywire.core.types.enums import FlowType, PortType, ShowWidgetStrategy, StoreStrategy
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.types.identity import DataTypeIdentity
from haywire.core.types.interface import IType
from haywire.core.types.utils import serialize_element_type

# Import the new DataField classes
from haywire.core.types.fields import DataField
from haywire.core.types.pipe import Pipe, Pipes

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.types.registry import TypeRegistry
    from haywire.core.node import NodeData


@dataclass
class DataPort(DataTypeIdentity):
    """
    Unified port for both inlets and outlets; direction is set by ``port_type``.
    """

    # Port identifier within node (different from registry_id!)
    id: str = ""

    port_type: PortType = PortType.UNDEFINED

    # Runtime data field (created by type in __post_init__)
    _data: DataField = field(init=False, repr=False, metadata={"serialize": False})
    """DataField instance storing port data (set in __post_init__)"""

    # Type tracking
    type_cls: type[IType] | None = field(default=None, metadata={"serialize": False})
    """The type class (FLOAT, ArrayType, etc.)"""

    # Edge state — two-tier storage
    _linked_edges: dict[str, EdgeWrapper] = field(
        default_factory=dict, repr=False, metadata={"serialize": False}
    )
    """Active linked EdgeWrapper instances. Used for pipe building."""

    # All EdgeWrapper instances targeting this port (linked + denied/displaced);
    # used for re-enablement when an active edge is removed.
    _all_edges: dict[str, EdgeWrapper] = field(
        default_factory=dict, repr=False, metadata={"serialize": False}
    )

    # Outlet-specific
    _pipes: Optional[Pipes] = field(default=None, repr=False, metadata={"serialize": False})

    allow_multiple_links: bool = False
    """Whether multiple links are allowed"""

    # Inlet-specific
    use_mode: str = "optional"

    # Internal: Store default override for field creation
    default: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def __hash__(self) -> int:
        """Hash by port id so DataPort can be used in sets."""
        return hash(self.id)

    def is_config(self) -> bool:
        """True for a config port, False for anything else."""
        return self.port_type == PortType.CONFIG

    def is_outlet(self) -> bool:
        """True for outlet, False for anything else"""
        return self.port_type == PortType.OUTLET

    def is_inlet(self) -> bool:
        """True for inlet, False for anything else"""
        return self.port_type == PortType.INLET

    # ========================================================================
    # HIERARCHY & ORGANIZATION
    # ========================================================================

    parent_group: Optional[str] = None
    """ID of parent group port, None if top-level"""

    section: Optional[str] = None
    """Section name for property panel grouping"""

    order: int = 0
    """Display order within parent"""

    is_group: bool = False
    """True if this port is a group container"""

    is_section: bool = False
    """True if this is a section marker (not rendered in node)"""

    needs_loopback: bool = False
    """Set to True if the control flow from this outlet needs to loop back to the node"""

    _is_dirty_structural: bool = False
    """Internal flag to track if port link has structurally changed"""

    _is_set_by_node: bool = field(default=False, metadata={"serialize": False})
    """Internal flag to indicate if the value was set via the node"""

    _pending_lazy_pipes: set = field(default_factory=set, metadata={"serialize": False})
    """Tracks Pipe objects needing lazy resolution at execution time."""

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    on_change: Optional[str] = None
    """Callback identifier to invoke when port value changes (e.g., 'reconfigure_ports')"""

    on_connect: Optional[str] = None
    """Callback identifier to invoke when connection is made"""

    on_disconnect: Optional[str] = None
    """Callback identifier to invoke when connection is broken"""

    widget: dict[str, Any] | None = field(default=None, repr=False, metadata={"serialize": False})
    """transient input only field. do not use other then in port creation"""

    widget_key: str | None = field(default=None)
    """Resolved widget key (set from widget["key"] in __post_init__)"""

    widget_config: dict[str, Any] = field(default_factory=dict)
    """Widget configuration dict (merged from widget["config"] in __post_init__)"""

    show_widget: ShowWidgetStrategy = ShowWidgetStrategy.NOT_LINKED
    """When the inline widget is rendered relative to link state. Per-direction
    defaults (inlet NOT_LINKED, outlet NEVER, config ALWAYS) are injected by
    as_inlet/as_outlet/as_config; override per-port via kwargs. See ADR 0003."""

    # Runtime reference (not serialized)
    _wrapper: Optional["NodeWrapper"] = field(default=None, repr=False, metadata={"serialize": False})

    _node: Optional["NodeData"] = field(default=None, repr=False, metadata={"serialize": False})
    """Reference to parent node (for callbacks)"""

    def __post_init__(self):
        """
        Create data field via type.
        """
        # Skip parent's post_init for runtime ports

        if self.widget:
            if not isinstance(self.widget, dict):
                raise ValueError(
                    f"Attribute 'widget' is of type: {type(self.widget).__name__}, "
                    f"but must be a dict with 'key' and optional 'config' fields. "
                    "Use WidgetClass.config(**kwargs) to generate correct format."
                )
            # Parse new widget dict format: {'key': '...', 'config': {...}}
            if "key" not in self.widget:
                raise ValueError(
                    "Attribute 'widget' is a dict and must contain the 'key' field. "
                    "Use WidgetClass.config(**kwargs) to generate correct format."
                )

            # Extract widget key and merge config into widget_config dict
            widget_key = self.widget["key"]
            widget_config = self.widget.get("config", {})

            # Merge widget config into widget_config dict (widget config takes precedence)
            self.widget_config = {**self.widget_config, **widget_config}
            self.widget_key = widget_key

            self.widget = None

        # Create data field — DataPort always needs a type_cls to be functional.
        if self.type_cls is None:
            raise ValueError(
                f"DataPort '{self.id}' constructed without type_cls. "
                f"DataPort instances must be created via from_spec()."
            )
        self._data = self.type_cls.create_field(default_override=self.default)

        # Hardcoded connection rules based on flow type and direction
        # They cannot be overridden by the user since they are fundamental to how the ports work
        if self.is_outlet():
            if self.flow_type == FlowType.DATA:
                # Data flow outlets allow multiple connections by design
                self.allow_multiple_links = True
            if self.flow_type == FlowType.CONTROL:
                # Control flow outlets do NOT allow multiple connections by design
                self.allow_multiple_links = False

        if self.is_inlet() and self.flow_type == FlowType.CONTROL:
            # Control flow inlets do allow multiple connections by design
            self.allow_multiple_links = True

        # contrary to data and control flow, callback flow does not have
        # hardcoded connection rules and can be freely configured by the user

    # ========================================================================
    # CALLBACK TRIGGERING
    # ========================================================================

    def _trigger_callback(self, callback_type: str, *args):
        """
        Trigger a callback by resolving the identifier.

        Examples:
            on_change='on_port_changed'  → nodeon_port_changed(port, old, new)
        """
        callback_name = getattr(self, callback_type)
        if not callback_name or not self._wrapper:
            return

        node = self._wrapper.node
        if hasattr(node, callback_name):
            method = getattr(node, callback_name)
            method(self, *args)
        else:
            raise ReferenceError(f"Node callback '{callback_name}' not found on node")

    # ========================================================================
    # VALUE MANAGEMENT
    # ========================================================================

    @property
    def data(self) -> DataField:
        """The port's underlying ``DataField`` (typed storage + ``on_changed``).

        Public accessor for the field; compound fields expose shape-specific
        helpers (``get_values_list()``, ``get_source_ids()``, ``get_item()``).
        """
        return self._data

    @property
    def stored_type(self) -> type[IType]:
        """The ``IType`` actually stored by this port's field (see ``DataField.get_stored_type``)."""
        return self._data.get_stored_type()

    def get_value(self) -> Any:
        """
        Get unwrapped value for worker convenience.

        Returns:
            - For PrimitiveField: Unwrapped primitive (42.0)
            - For BaseField: BaseType instance (MeshData(...))
            - For CompoundField: Container (dict, list, etc.)
            - None if no data
        """
        if not self._data:
            return None

        return self._data.get_value()

    def set_value(self, new_value: Any, edge_id: str | None = None) -> None:
        """
        Set port value. Single entry point for all value updates.

        For inlets:
        - Widget/programmatic (no edge_id) with on_change: fire immediately
        - Edge-driven (edge_id set) or no callback: defer to resolve_dirty_data()

        For outlets:
        - Fire on_change immediately, then propagate to downstream inlets

        Args:
            new_value: Value to set (can be IType instance or raw value)
            edge_id: Source identifier (set when value comes via Pipe.pull())
        """
        if not self._data:
            return

        self._data.set_value(new_value, source_id=edge_id)

        if self.is_inlet():
            # Inlet values come from an edge (edge_id set) or a widget/programmatic
            # set — never from the owning node, so clear the node-set flag.
            self._is_set_by_node = False
            if edge_id is None and self.on_change is not None:
                # Widget/programmatic change → fire on_change immediately
                self._trigger_callback("on_change", new_value)
            else:
                # Edge-driven OR no callback → defer to resolve_dirty_data()
                self._mark_as_data_dirty()
        else:
            # Outlet: the node is always the setter (out() is the only caller).
            self._is_set_by_node = True
            # Fire on_change immediately (node is the setter)
            if self.on_change is not None:
                self._trigger_callback("on_change", new_value)
            if self._pipes is not None:
                self._pipes.propagate()

    # ========================================================================
    # Lazy Propagation
    # ========================================================================

    def resolve_dirty_data(self) -> None:
        """
        Resolve dirty data: pull lazy pipes, then fire deferred on_change.

        Called at the start of node execution, before on_validate and worker.
        """
        # 1. Pull data from lazy pipes
        while self._pending_lazy_pipes:
            pipe = self._pending_lazy_pipes.pop()
            pipe.pull()

        # 2. Fire deferred on_change (covers both eager pushes and lazy pulls)
        if self.on_change is not None:
            self._trigger_callback("on_change", self.get_value())

    def _mark_as_data_dirty(self, pipe: "Pipe | None" = None) -> None:
        """
        Mark the port as data dirty and inform the node.

        Args:
            pipe: Pipe instance for lazy pull (only set for lazy edges)
        """
        if self._node:
            if pipe is not None:
                self._pending_lazy_pipes.add(pipe)
            self._node.mark_port_as_dirty(self)

    # ========================================================================
    # LINK MANAGEMENT
    # ========================================================================

    def is_linked(self) -> bool:
        """Check if port has any linked edges"""
        return len(self._linked_edges) > 0

    def should_show_widget(self) -> bool:
        """
        Resolve whether this port's inline widget should be rendered, given its
        ``show_widget`` strategy and current link state. See ADR 0003.

        Note: this does NOT check ``widget_key`` — a caller must still confirm the
        port has a widget to render. It answers only the strategy-vs-link question.
        """
        strategy = self.show_widget
        if strategy == ShowWidgetStrategy.ALWAYS:
            return True
        if strategy == ShowWidgetStrategy.NEVER:
            return False
        if strategy == ShowWidgetStrategy.WHEN_LINKED:
            return self.is_linked()
        # NOT_LINKED
        return not self.is_linked()

    def adopt_state_from(self, existing: "DataPort") -> None:
        """Transplant edge state (and value, when types match) from a port being
        replaced during reconfiguration. Called by ``BaseNode.add`` when a port id
        is re-added in a push/rejig context.
        """
        self._linked_edges = existing._linked_edges.copy()
        self._all_edges = existing._all_edges.copy()

        # Preserve the field instance only when the type is unchanged, so the
        # stored value (and its observers) survive the port swap.
        if existing._data is not None and self._data is not None:
            if existing.type_cls is self.type_cls:
                self._data = existing._data

    def _add_link(self, edge_wrapper: EdgeWrapper) -> EdgeWrapper | None:
        """
        Attempt to link an edge to this port.

        Always tracks in _all_edges. If the port is single-connection and
        already has a linked edge, the old edge is displaced (removed from
        _linked_edges but remains in _all_edges).

        Args:
            edge_wrapper: EdgeWrapper to link

        Returns:
            The displaced EdgeWrapper if one was replaced, None otherwise
        """
        displaced: EdgeWrapper | None = None

        # Always track in _all_edges
        self._all_edges[edge_wrapper.edge_id] = edge_wrapper

        if edge_wrapper.edge_id not in self._linked_edges:
            if not self.allow_multiple_links:
                old_wrapper_uuid = next(iter(self._linked_edges), None)
                if old_wrapper_uuid:
                    displaced = self._linked_edges.pop(old_wrapper_uuid)
                    self._data.remove_source(old_wrapper_uuid)
                    if self.on_disconnect and displaced:
                        self._trigger_callback("on_disconnect", displaced)
                self._linked_edges = {edge_wrapper.edge_id: edge_wrapper}
            else:
                self._linked_edges[edge_wrapper.edge_id] = edge_wrapper

            if self.on_connect:
                self._trigger_callback("on_connect", edge_wrapper)

        # Mark structurally dirty in any case because even if the
        # connection already exists, it may have been reconnected to a
        # different source during edge validation
        self._mark_as_structuraly_dirty()

        return displaced

    def _get_linked_edges_uuid(self) -> list[str]:
        """
        Get list of linked edge UUIDs.

        Returns:
            List of EdgeWrapper UUIDs linked to this port
        """
        return list(self._linked_edges.keys())

    def _is_linked_to(self, wrapper_uuid: str) -> bool:
        """
        Check if linked to given edge.
        Args:
            wrapper_uuid: UUID of EdgeWrapper to check
        Returns:
            True if linked, False otherwise
        """
        return wrapper_uuid in self._linked_edges

    def _clear_link(self, wrapper_uuid: str) -> None:
        """
        Remove an edge from the linked set only (stays in _all_edges).
        Called when an edge is displaced or loses functionality.

        Args:
            wrapper_uuid: UUID of EdgeWrapper to unlink
        """
        if wrapper_uuid in self._linked_edges:
            edge_wrapper = self._linked_edges.pop(wrapper_uuid)
            self._data.remove_source(wrapper_uuid)
            self._mark_as_structuraly_dirty()

            if self.on_disconnect and edge_wrapper:
                self._trigger_callback("on_disconnect", edge_wrapper)

    def _remove_edge(self, wrapper_uuid: str) -> None:
        """
        Fully remove an edge from both _linked_edges and _all_edges.
        Called when an edge is explicitly deleted or the port is destroyed.

        Args:
            wrapper_uuid: UUID of EdgeWrapper to remove entirely
        """
        if wrapper_uuid in self._linked_edges:
            self._clear_link(wrapper_uuid)
        self._all_edges.pop(wrapper_uuid, None)

    def _try_reenable(self) -> EdgeWrapper | None:
        """
        After an active edge is removed, scan _all_edges for a functional
        candidate to promote to linked. Uses FIFO order (dict insertion order).

        Only applicable for single-connection ports that have no linked edge.

        Returns:
            The re-enableable EdgeWrapper, or None if none found.
            Caller is responsible for calling candidate.link().
        """
        if self.allow_multiple_links:
            return None

        if self._linked_edges:
            return None  # Already has a linked edge

        for uuid, edge in self._all_edges.items():
            if uuid not in self._linked_edges and edge.is_functional():
                return edge

        return None

    def _detach_all_edges(self) -> list[EdgeWrapper]:
        """
        Remove all edges from both tiers. Used during port destruction (push/pop).

        Returns:
            List of all edges that were being tracked, so the caller can
            notify them of port destruction.
        """
        all_edges = list(self._all_edges.values())
        self._linked_edges.clear()
        self._all_edges.clear()
        return all_edges

    def get_valid_edges(self) -> list[EdgeWrapper]:
        """
        Get list of valid linked EdgeWrappers.

        Returns:
            List of valid EdgeWrapper instances linked to this port
        """
        return [edge_wrapper for edge_wrapper in self._linked_edges.values() if edge_wrapper.is_valid()]

    def _mark_as_structuraly_dirty(self) -> None:
        """Mark the port's node as structurally dirty."""
        self._is_dirty_structural = True

    def _housekeeping(self) -> None:
        """
        Called during graph housekeeping phase.
        Rebuild connection pipes after structural changes (like reconnecting edges).
        This cannot be done immediately upon link changes since
        at the time of a link change, the edges are not yet validated.
        """
        if self._is_dirty_structural:
            self._refresh_pipes()
            # as soon as we refresh pipes, propagate current value
            if self._pipes:
                self._pipes.propagate()
        self._is_dirty_structural = False

    def _refresh_pipes(self) -> None:
        """
        Refresh pipes based on current link state.
        If outlet and linked, ensure pipes exist and are up-to-date.
        If outlet and unlinked, clear pipes.
        Called during graph housekeeping phase.
        """
        if self.is_outlet():
            if self.is_linked():
                if self._pipes is None:
                    self._pipes = Pipes(outlet_port=self)
                self._pipes.clear()
                for wrapper in self.get_valid_edges():
                    self._pipes.add_pipe(wrapper)
            else:
                if self._pipes:
                    self._pipes.clear()
                    self._pipes = None

    # ========================================================================
    # PORT TYPE CHECKS
    # ========================================================================

    def has_pin(self) -> bool:
        """Whether this port renders a connection pin on the canvas.

        Config ports are panel-only (no pin); every inlet/outlet renders one.
        """
        return not self.is_config()

    def is_callback_pin(self) -> bool:
        """Check if this is a callback pin"""
        return self.flow_type == FlowType.CALLBACK

    def is_control_pin(self) -> bool:
        """Check if this is a control pin"""
        return self.flow_type == FlowType.CONTROL

    def is_data_pin(self) -> bool:
        """Check if this is a data pin"""
        return self.flow_type == FlowType.DATA

    # ========================================================================
    # FACTORY
    # ========================================================================

    @classmethod
    def from_spec(
        cls,
        spec: dict,
        type_registry: "TypeRegistry",
        wrapper: "NodeWrapper",
        node: "NodeData",
    ) -> "DataPort":
        """
        Create a DataPort from a PortSpec dict.

        Resolves the type from the spec and creates a DataPort instance
        with wrapper reference available immediately.

        Note: CompoundType validation is done at spec creation time (as_inlet/as_outlet),
        so we trust the spec here.

        Args:
            spec: PortSpec from as_inlet/as_outlet/as_config or to_dict
            type_registry: Registry to resolve type classes
            wrapper: NodeWrapper to attach to the port
            node: BaseNode to attach to the port
        Returns:
            Instantiated DataPort
        """
        kwargs = spec["kwargs"].copy()
        recipe = spec["recipe"]

        # Resolve type class (handles compound types via element_type)
        type_cls = type_registry.resolve_type_from_spec(recipe)

        # Build port kwargs - spec already contains merged identity + user values
        flow_type = FlowType(kwargs.pop("flow_type", FlowType.DATA.value))
        port_type = PortType(kwargs.pop("port_type", PortType.UNDEFINED.value))

        # show_widget arrives as a raw string from JSON; reconstruct the enum.
        # Absent means the field's static default applies (as_inlet/as_outlet/
        # as_config inject the per-direction default at spec-creation time).
        if "show_widget" in kwargs:
            kwargs["show_widget"] = ShowWidgetStrategy(kwargs["show_widget"])

        # store_strategy serializes to a raw int (IntFlag); reconstruct the enum
        # so the round-tripped port keeps its should_store() behaviour. Absent
        # means the field's static default applies.
        if "store_strategy" in kwargs:
            kwargs["store_strategy"] = StoreStrategy(kwargs["store_strategy"])

        # Freeform constructor-kwargs bag (mirrors PortSpec.kwargs: Dict[str, Any]).
        # Annotated explicitly so the merge of the Any-valued spec kwargs with the
        # typed literals below stays Any rather than widening to a concrete union
        # that a type checker would then check key-by-key against cls.__init__.
        port_kwargs: dict[str, Any] = {
            **kwargs,  # Spec already has identity + user overrides
            "flow_type": flow_type,
            "port_type": port_type,
            "type_cls": type_cls,
            "_wrapper": wrapper,
            "_node": node,
        }

        # Create port
        port = cls(**port_kwargs)

        # Let type configure port (for compound types, etc.)
        type_cls._configure_port(port)

        # Restore field data if present (backward compatible)
        if "field_data" in spec:
            port._data.from_dict(spec["field_data"])

        return port

    def to_dict(self, include_data: bool = True) -> dict:
        """
        Serialize port using field metadata for control.

        Args:
            include_data: If True, includes field values (when store_data is also True)

        Returns:
            dict: Serialized port representation
        """
        assert self.type_cls is not None  # __post_init__ enforces this
        result: dict[str, Any] = {
            "kwargs": {},
            "recipe": serialize_element_type(self.type_cls),
        }

        # Iterate over dataclass fields
        for f in fields(self):
            # Skip fields marked as non-serializable
            if not f.metadata.get("serialize", True):
                continue

            value = getattr(self, f.name)

            # Skip if default value
            if f.default is not MISSING and value == f.default:
                continue
            if f.default_factory is not MISSING and value == f.default_factory():
                continue

            # Transform enums
            if isinstance(value, FlowType):
                value = value.value
            if isinstance(value, PortType):
                value = value.value
            if isinstance(value, ShowWidgetStrategy):
                value = value.value
            if isinstance(value, StoreStrategy):
                value = value.value

            result["kwargs"][f.name] = value

        # Optionally serialize field data
        if include_data and self._data:
            if self.store_strategy.should_store(
                is_linked=self.is_linked(),
                has_widget=self.widget_key is not None,
                node_set=self._is_set_by_node,
            ):
                result["field_data"] = self._data.to_dict()

        return result
